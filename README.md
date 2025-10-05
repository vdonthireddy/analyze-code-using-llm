# Setup Guide for macOS: Docker with Ollama & Python 3.13.1 via pyenv

This README covers the setup steps on macOS to:

- Install Docker
- Pull the Ollama Docker image and access Llama 3.2
- Install pyenv
- Install Python 3.13.1 using pyenv and activate it

---

## Prerequisites

- macOS system with administrator privileges
- Internet connection

---

## Step 1: Install Docker Desktop for Mac

1. Download Docker Desktop for Mac from the official Docker website:

   https://www.docker.com/products/docker-desktop/

2. Open the downloaded `.dmg` file and drag the Docker.app to the Applications folder.

3. Launch Docker from Applications.

4. Follow any onboarding instructions. Check Docker is running by opening Terminal and running:

   ```
   docker --version
   ```

   Expected output should show the Docker version installed.

---

## Step 2: Pull Ollama Docker Image and Llama 3.2

1. Open Terminal.

2. Pull the Ollama Docker image (replace `ollama` with the exact image name if different):

   ```
   docker pull ollama/ollama
   ```

3. Run a container from the image (bash shell example):

   ```
   docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
   ```

4. Inside the container, pull the Llama 3.2 model (replace with actual model pull command if needs specific CLI):

   ```
   docker exec -it ollama ollama pull llama3.2
   ```

---

## Step 3: Install pyenv on macOS

1. Install Homebrew if you don't have it (run this in Terminal):

   ```
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. Install pyenv dependencies and pyenv via Homebrew:

   ```
   brew update
   brew install pyenv
   ```

3. Add pyenv to your shell environment:

   For **Zsh** (default on macOS Catalina and later), add to `~/.zshrc`:

   ```
   echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
   echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
   echo 'eval "$(pyenv init --path)"' >> ~/.zprofile
   echo 'eval "$(pyenv init -)"' >> ~/.zshrc
   ```

   For **Bash** (if using bash), add to `~/.bash_profile`:

   ```
   echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bash_profile
   echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bash_profile
   echo 'eval "$(pyenv init --path)"' >> ~/.bash_profile
   echo 'eval "$(pyenv init -)"' >> ~/.bash_profile
   ```

4. Restart your terminal or reload your shell configuration:

   ```
   source ~/.zshrc
   # or
   source ~/.bash_profile
   ```

5. Verify pyenv installed:

   ```
   pyenv --version
   ```

---

## Step 4: Install and Activate Python 3.13.1 with pyenv

1. Install Python 3.13.1:

   ```
   pyenv install 3.13.1
   ```

2. Set Python 3.13.1 as the global version:

   ```
   pyenv global 3.13.1
   ```

3. Verify the active Python version:

   ```
   python --version
   ```

   It should display `Python 3.13.1`.

---

## Troubleshooting

- If Docker commands give permission errors, ensure Docker Desktop is running and you have correct permissions.
- If pyenv commands do not work after installation, ensure the shell profile files are correctly updated and sourced.

---

Now the environment is set up with Docker running Ollama and Python 3.13.1 managed via pyenv on macOS.

---

## Install the required modules to run the code

```
pip install -r ./requirements.txt
```

### Make sure you have an .env file with following configuration
```
USE_OLLAMA=true
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434
```

### Run the code
```
python main.py
```
#### This code will take a while if you execute it on your local Mac... Good luck and enjoy!