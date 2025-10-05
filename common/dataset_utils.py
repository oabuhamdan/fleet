import shutil
from pathlib import Path
from typing import Union, Optional

import datasets
from datasets import get_dataset_split_names, DatasetDict, Dataset
from flwr_datasets import FederatedDataset
from flwr_datasets import partitioner
from torch.utils.data import DataLoader
from torchvision.transforms import transforms

from common.configs import DatasetConfig
from common.loggers import warning, info

WARNING_RECREATE_MESSAGE = (
    f"You can recreate the dataset by setting the force_create to true.\n"
)


def _process_dataset_name(name):
    """Process dataset name to ensure it is in lowercase and without special characters."""
    return name.lower().replace(" ", "_").replace("-", "_").replace(".", "_").replace("/", "_")


def prepare_datasets(cfg: DatasetConfig):
    clean_name = _process_dataset_name(cfg.name)
    data_path = f"{cfg.path}/{clean_name}"

    if Path(data_path).exists():
        if cfg.force_create:
            info(f"Removing existing dataset at '{data_path}' as 'force_create' is True.")
            shutil.rmtree(data_path)
        else:
            info(f"Dataset '{cfg.name}' already exists at '{data_path}'.")
            return

    partitioner_cls = getattr(partitioner, cfg.partitioner.id)
    train_partitioner = partitioner_cls(**cfg.partitioner.kwargs)
    has_test = "test" in get_dataset_split_names(cfg.name)

    # Handle server_eval when test split doesn't exist
    if cfg.server_eval and not has_test:
        warning(f"server_eval=True but dataset '{cfg.name}' has no test split. Server evaluation will be skipped.")

    # Configure partitioners
    partitioners = {"train": train_partitioner}
    if has_test:
        partitioners["test"] = 1 if cfg.server_eval else partitioner_cls(**cfg.partitioner.kwargs)

    fds = FederatedDataset(dataset=cfg.name, partitioners=partitioners)
    if cfg.server_eval and has_test:
        info("Saving centralized test split for server evaluation.")
        fds.partitioners["test"].dataset.save_to_disk(f"{data_path}/server_eval")

    for partition_id in range(fds.partitioners["train"].num_partitions):
        train_ds = fds.partitioners["train"].load_partition(partition_id)
        if cfg.server_eval:
            dset = DatasetDict({"train": train_ds})
        else:
            if has_test:
                test_ds = fds.partitioners["test"].load_partition(partition_id)
                dset = DatasetDict({"train": train_ds, "test": test_ds})
            else:
                dset = train_ds.train_test_split(test_size=cfg.test_size)

        dset.save_to_disk(f"{data_path}/{partition_id + 1}")


def get_partition(path, name, partition_id) -> Optional[Union[Dataset, DatasetDict]]:
    name = _process_dataset_name(name)
    data_path = f"{path}/{name}/{partition_id}"

    if not Path(data_path).exists():
        warning(f"Dataset '{name}' not found at '{path}' or partition {partition_id} doesn't exist")
        warning(WARNING_RECREATE_MESSAGE)
        return None
    partition: Union[Dataset, DatasetDict] = datasets.load_from_disk(data_path)
    return partition


def get_client_partition(path, name, partition_id) -> DatasetDict:
    dataset_dict = get_partition(path, name, partition_id)
    assert dataset_dict, f"Dataset '{name}' not found at '{path}'.\n{WARNING_RECREATE_MESSAGE}"
    assert isinstance(dataset_dict, DatasetDict), f"Dataset '{name}' is not a DatasetDict."
    return dataset_dict

def get_server_eval_dataset(path, name) -> Optional[Dataset]:
    dataset = get_partition(path, name, "server_eval")
    if not dataset:
        return None

    assert isinstance(dataset, Dataset), f"Server eval dataset '{name}' is not a Dataset."
    return dataset

def get_dataloader(dataset: Dataset, transform, batch_size: int, **dataloader_kwargs) -> DataLoader:
    dataset = dataset.with_transform(transform)
    dataloader = DataLoader(dataset, batch_size=batch_size, **dataloader_kwargs)
    return dataloader


def basic_img_transform(img_key):
    img_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(0.5, 0.5)
    ])

    def apply(batch):
        batch[img_key] = [img_transform(row) for row in batch[img_key]]
        return batch

    return apply

# @hydra.main(config_path="../static/config/dataset", config_name="default", version_base=None)
# def script_call(cfg: DatasetConfig):
#     configure_logger("default", False, None, "INFO")
#     prepare_datasets(cfg)
#
#
# if __name__ == "__main__":
#     script_call()
