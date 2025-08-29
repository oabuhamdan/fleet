from collections import OrderedDict

import torch
import torch.nn as nn
import torch.nn.functional as F

from common.loggers import info


class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        self.conv1 = nn.Conv2d(3, 6, 5)
        self.pool = nn.MaxPool2d(2, 2)
        self.conv2 = nn.Conv2d(6, 16, 5)
        self.fc1 = nn.Linear(16 * 5 * 5, 120)
        self.fc2 = nn.Linear(120, 84)
        self.fc3 = nn.Linear(84, 10)

    def forward(self, x):
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = x.view(-1, 16 * 5 * 5)
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return self.fc3(x)


def get_weights(model: nn.Module, ):
    """Return the model weights as a list of NumPy arrays."""
    return [val.cpu().numpy() for _, val in model.state_dict().items()]


def set_weights(model: nn.Module, parameters):
    """Set the model weights from a list of NumPy arrays."""
    params_dict = zip(model.state_dict().keys(), parameters)
    state_dict = OrderedDict({k: torch.tensor(v) for k, v in params_dict})
    model.load_state_dict(state_dict, strict=True)


def train(
        model: nn.Module,
        trainloader,
        device,
        optimizer,
        loss_fn,
        epochs: int = 1,
        input_key: str = "inputs",
        target_key: str = "targets",
        scheduler=None,
        log_interval: int = 100,
        **kwargs
):
    """Train the model for a number of epochs."""
    model.to(device)
    model.train()
    running_loss = 0.0
    for epoch in range(epochs):
        for i, batch in enumerate(trainloader):
            inputs = batch[input_key].to(device)
            targets = batch[target_key].to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = loss_fn(outputs, targets)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
            if i % log_interval == 0:
                info(f"Epoch {epoch} - Step {i}")
        if scheduler is not None:
            scheduler.step()
    train_loss = running_loss / (epochs * len(trainloader.dataset))  # Average loss per sample
    return train_loss


def test(
        model: nn.Module,
        testloader,
        device,
        loss_class=nn.CrossEntropyLoss,
        input_key: str = "inputs",
        target_key: str = "targets"
):
    """Evaluate the model and return average eval_loss and eval_accuracy."""
    model.to(device)
    loss_fn = loss_class().to(device)
    model.eval()
    correct, loss_total, total = 0, 0, 0
    with torch.no_grad():
        for batch in testloader:
            inputs = batch[input_key].to(device)
            targets = batch[target_key].to(device)
            outputs = model(inputs)
            loss_total += loss_fn(outputs, targets).item()
            _, predicted = torch.max(outputs.data, 1)
            correct += (predicted == targets).sum().item()
            total += targets.size(0)
    eval_accuracy = correct / total if total > 0 else 0
    eval_loss = loss_total / len(testloader) if len(testloader) > 0 else 0
    return eval_loss, eval_accuracy
