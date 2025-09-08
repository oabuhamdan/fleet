from dataclasses import field, dataclass
from pathlib import Path

import datasets
import hydra
from datasets import get_dataset_split_names
from flwr_datasets import FederatedDataset
from flwr_datasets import partitioner
from torch.utils.data import DataLoader
from torchvision.transforms import transforms
from transformers import AutoTokenizer

from common.loggers import configure_logger, warning


@dataclass
class DatasetConfig:
    path: str = "static/data"
    name: str = "cifar10"
    partitioner_cls_name: str = "IidPartitioner"
    partitioner_kwargs: dict = field(default_factory=dict)
    force_create: bool = False
    test_size: float = 0.2
    fed_eval: bool = True


def _process_dataset_name(name):
    """Process dataset name to ensure it is in lowercase and without special characters."""
    return name.lower().replace(" ", "_").replace("-", "_").replace(".", "_").replace("/", "_")


def prepare_datasets(cfg: DatasetConfig):
    clean_name = _process_dataset_name(cfg.name)
    data_path = f"{cfg.path}/{clean_name}"
    if not cfg.force_create and Path(data_path).exists():
        return
    partitioner_cls = getattr(partitioner, cfg.partitioner_cls_name)
    partitioner_instance = partitioner_cls(**cfg.partitioner_kwargs)

    splits = get_dataset_split_names(cfg.name)
    if not cfg.fed_eval and "test" not in splits:
        warning("Dataset does not have a 'test' split. Switching to federated testing.")
        fed_eval = True

    partitioners = {"train": partitioner_instance} if cfg.fed_eval else {"train": partitioner_instance, "test": 1}
    fds = FederatedDataset(dataset=cfg.name, partitioners=partitioners)
    if cfg.fed_eval:
        for partition_id in range(partitioner_instance.num_partitions):
            partition = fds.load_partition(partition_id)
            partition = partition.train_test_split(test_size=cfg.test_size)
            partition.save_to_disk(f"{data_path}/{partition_id + 1}")
    else:
        testset = fds.load_split("test")
        testset.save_to_disk(f"{data_path}/server_eval")
        for partition_id in range(partitioner_instance.num_partitions):
            partition = fds.load_partition(partition_id, "train")
            partition.save_to_disk(f"{data_path}/{partition_id + 1}")


def get_partition(path, name, partition_id):
    name = _process_dataset_name(name)
    data_path = f"{path}/{name}"
    assert Path(data_path).exists(), "Dataset does not exist."

    partition = datasets.load_from_disk(f"{data_path}/{partition_id}")
    return partition


def process_img_dataset(dataset, img_key="img", extra_transforms=None):
    all_transforms = [transforms.ToTensor(), transforms.Normalize((0.5,), (0.5,))]
    if extra_transforms:
        all_transforms.extend(extra_transforms)

    transformer = transforms.Compose(all_transforms)

    def apply_transforms(batch):
        batch[img_key] = [transformer(img) for img in batch[img_key]]
        return batch

    dataset = dataset.with_transform(apply_transforms)
    return dataset


def process_text_dataset(dataset, text_key, tokenizer=None, **tokenizer_kwargs):
    tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased") if tokenizer is None else tokenizer

    def apply_tokenizer(batch):
        batch[text_key] = [tokenizer(text, **tokenizer_kwargs) for text in batch[text_key]]
        return batch

    dataset = dataset.with_transform(apply_tokenizer)
    return dataset


def get_dataloader(dataset_path, dataset_name, partition_id, batch_process=None,
                   dataset_type="img", split="train", batch_size=32, **dataloader_kwargs):
    dataset = get_partition(dataset_path, dataset_name, partition_id)
    if split not in dataset:
        warning(f"Split '{split}' not found in the dataset. Available splits: {dataset.keys()}")
        return None

    dataset = dataset[split]
    if dataset_type == "img":
        dataset = process_img_dataset(dataset, img_key="img", extra_transforms=batch_process)
    elif dataset_type == "text":
        dataset = process_text_dataset(dataset, text_key="text", tokenizer=batch_process)

    return DataLoader(dataset, batch_size=batch_size, **dataloader_kwargs)


# @hydra.main(config_path="../static/config/dataset", config_name="default", version_base=None)
# def script_call(cfg: DatasetConfig):
#     configure_logger("default", False, None, "INFO")
#     prepare_datasets(cfg)
#
#
# if __name__ == "__main__":
#     script_call()
