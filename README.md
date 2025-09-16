# Federated Learning Emulation and Evaluation Testbed  

![Cover Image](https://oabuhamdan.com/app/static/media/images/fleet.original.jpg)  

## 🚀 Introduction  

The **Federated Learning Emulation and Evaluation Testbed** provides a **highly configurable, extensible, and reproducible environment** for running **federated learning (FL) experiments** under realistic network conditions.  

At its core, the testbed integrates:  
- **[Flower (Flwr)](https://flower.ai/):** a framework-agnostic FL library.  
- **[Containernet](https://containernet.github.io/):** a Docker-based network emulator.  
- **[Hydra](https://hydra.cc/)** (from **Facebook Research**): for unified configuration management.  

Each FL participant runs inside a Docker container, interconnected through an emulated network with precisely controlled characteristics (latency, bandwidth, packet loss, etc.).  
The testbed also supports **background traffic generation** and **link congestion emulation**, enabling more realistic experimental conditions.  

The workflow is **fully orchestrated with Hydra** and YAML-based configuration, making it:  
- 🔧 Easy to configure.  
- 📦 Quick to set up with default settings.  
- 📊 Rich in metrics (training logs, system logs, and experiment results).  

This bridges the gap between **pure FL simulations** and **real-world deployments**, enabling researchers to jointly evaluate **algorithmic performance** and **network dynamics**.  

---
## 📚 Reference

If you use this testbed in your research, please cite our work:

```
@misc{hamdan2025fleet,
      title={FLEET: A Federated Learning Emulation and Evaluation Testbed for Holistic Research}, 
      author={Osama Abu Hamdan and Hao Che and Engin Arslan and Md Arifuzzaman},
      year={2025},
      eprint={2509.00621},
      archivePrefix={arXiv},
      primaryClass={cs.NI},
      url={https://arxiv.org/abs/2509.00621}, 
}
```
---

## 📝 FLEET Tutorial

A complete tutorial for FLEET is available as a series of blog posts here:
[(FLEET Blog)](https://www.oabuhamdan.com/blog/?tag=FLEET )

---
## ⚡ Quickstart  

### Prerequisites
- Unix System (tested on Ubuntu 22.04)  
- [Open vSwitch](https://docs.openvswitch.org/en/latest/intro/install/distributions/)
- [Docker](https://docs.docker.com/engine/install/)
- Python 3.10+
- Python Venv

### Installation
```bash
git clone https://github.com/oabuhamdan/fleet.git
cd fleet
````
#### 1️⃣ Auto Setup (recommended)

Run the provided setup script:

```bash
bash config.sh
```

This script will:

* Double check required dependencies.
* Create a Python virtual environment (`.venv/`).
* Install Python dependencies.
* Install a proper PyTorch version (CPU or GPU)
* Install Containernet.
* Build Docker images required for the testbed.

#### 2️⃣ Manual Setup

If you prefer to configure things manually:  

1. **Create and activate a virtual environment:**  

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ````

2. **Install Python dependencies:**

   ```bash
   pip install -r requirements.txt
   ```
3. **Install PyTorch:**

   **PyTorch CPU** and **PyTorch CUDA** are two versions of the PyTorch library that differ in where computations are performed; on the system's CPU or on an NVIDIA GPU via CUDA.

   **Comparison**:

   | Feature              | PyTorch CPU                  | PyTorch CUDA                    |
   |----------------------|------------------------------|---------------------------------|
   | **Computation**      | Runs on the CPU              | Runs on NVIDIA GPUs using CUDA  |
   | **Install Size**     | Lighter (~200 MB)            | Heavier (800 MB or more)        |
   | **Hardware Needed**  | Works on any system          | Requires NVIDIA GPU + drivers   |

   If you have a CPU-only machine, install PyTroch CPU with:

   ```bash
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
   ```

   If you have a machine with an NVIDIA GPU, install PyTroch Cuda with:
   ```bash
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
   ```

3. **Install Containernet:**

   Clone the repository:

   ```bash
   git clone https://github.com/containernet/containernet.git
   ```

   Install it inside your virtual environment:

   ```bash
   cd containernet
   pip install .   # make sure your venv is active
   cd ..
   ```

4. **Build Docker images for FLEET:**

   ```bash
   docker build -t fleet-fl -f static/docker/Dockerfile-FL .
   docker build -t fleet-bg -f static/docker/Dockerfile-BG .
   ```

### Running the Default Experiment  

We provide a default configuration file for a quick start.  
> **Note:** Containernet requires `sudo` permissions to run and create the topology.  

```bash
sudo .venv/bin/python main.py
````

This will:

1. Set up the emulated network.
2. Deploy FL participants in Docker containers.
3. Download and partition the dataset.
4. Start Containernet’s interactive CLI.


#### Starting the Experiment from the CLI

Once inside the CLI, you can start, stop, and manage experiments.
To launch the federated learning workflow:

```bash
containernet> py net.start_experiment()
```

This command will:

1. Ping all FL clients to ensure connectivity.
2. Start the FL training process.

By default, the FL server will stop automatically after completing all configured rounds.


#### Logs and Results

After the run, you’ll find both **FL training logs** and **network logs** stored at:

```
./static/logs/my_experiment-<timestamp>/
```

#### Exiting the CLI  

To exit the CLI and clean up the network, press:  

```
Ctrl + D
```

If at any time **FLEET exits with an error**, you should manually clean up the network before starting it again with:

```
sudo ./venv/bin/mn -c
```

---

## 🤝 Contributing

We welcome contributions of all kinds:

* Bug fixes
* Feature extensions
* Documentation improvements
* Example configurations

To contribute:

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/my-feature`).
3. Commit your changes (`git commit -m "Add my feature"`).
4. Push the branch (`git push origin feature/my-feature`).
5. Open a Pull Request.

Please follow the coding style and ensure everything is working before submitting.

---

## 📜 License

This project is licensed under the **Apache License 2.0**.
See the [LICENSE](./LICENSE) file for details.

---
## 👤 Maintainers
This project is developed and maintained by **[Osama Abu Hamdan](https://oabuhamdan.com)**.  
