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
    f"Returning None."
)


def _process_dataset_name(name):
    """Process dataset name to ensure it is in lowercase and without special characters."""
    return name.lower().replace(" ", "_").replace("-", "_").replace(".", "_").replace("/", "_")


def prepare_datasets(cfg: DatasetConfig):
    clean_name = _process_dataset_name(cfg.name)
    data_path = f"{cfg.path}/{clean_name}"
    if Path(data_path).exists():
        if cfg.force_create:
            info("Removing existing dataset at '{data_path}' as 'force_create' is True.")
            shutil.rmtree(data_path)
        else:
            info(f"Dataset '{cfg.name}' already exists at '{data_path}'.")
        return
    partitioner_cls = getattr(partitioner, cfg.partitioner.id)
    partitioner_instance = partitioner_cls(**cfg.partitioner.kwargs)

    splits = get_dataset_split_names(cfg.name)
    if cfg.server_eval and "test" not in splits:
        warning("Dataset does not have a 'test' split. Server evaluation will be skipped.")
        cfg.server_eval = False

    partitioners = {"train": partitioner_instance}
    if cfg.server_eval:
        partitioners["test"] = 1

    fds = FederatedDataset(dataset=cfg.name, partitioners=partitioners)
    if cfg.server_eval:
        testset = fds.load_split("test")
        testset.save_to_disk(f"{data_path}/server_eval")
        for partition_id in range(partitioner_instance.num_partitions):
            partition = fds.load_partition(partition_id, "train")
            partition.save_to_disk(f"{data_path}/{partition_id + 1}")
    else:
        for partition_id in range(partitioner_instance.num_partitions):
            partition = fds.load_partition(partition_id)
            partition = partition.train_test_split(test_size=cfg.test_size)
            partition.save_to_disk(f"{data_path}/{partition_id + 1}")


def get_partition(path, name, partition_id) -> Optional[Union[Dataset, DatasetDict]]:
    name = _process_dataset_name(name)
    data_path = f"{path}/{name}"

    partition: Union[Dataset, DatasetDict] = datasets.load_from_disk(f"{data_path}/{partition_id}")
    if partition is None:
        warning(f"Dataset '{name}' not found at '{data_path}'.\n{WARNING_RECREATE_MESSAGE}")
        return None
    return partition


def get_train_dataset(path, name, partition_id, key) -> Dataset:
    dataset = get_partition(path, name, partition_id)
    assert dataset, f"Dataset '{name}' not found at '{path}'.\n{WARNING_RECREATE_MESSAGE}"

    if isinstance(dataset, DatasetDict):
        assert key in dataset, f"Key '{key}' not found in dataset '{name}'."
        dataset = dataset[key]

    info("Returning the whole dataset as it does not have splits.")
    return dataset


def get_test_dataset(path, name, partition_id, key=None) -> Optional[Dataset]:
    dataset = get_partition(path, name, partition_id)
    if not dataset:
        return None

    if partition_id == "server_eval":
        return dataset

    if isinstance(dataset, DatasetDict) and key in dataset:
        return dataset[key]

    return None


def get_dataloader(dataset: Dataset, transform, batch_size: int, **dataloader_kwargs) -> DataLoader:
    dataset = dataset.with_transform(transform)
    dataloader = DataLoader(dataset, batch_size=batch_size, **dataloader_kwargs)
    return dataloader


def basic_img_transform():
    img_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
    ])

    def apply(batch):
        batch["img"] = [img_transform(row) for row in batch["img"]]
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
