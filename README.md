# requirements.txt -- these version are compatible with python version 3.13.1
```
langchain>=0.1.0,<0.3.0
langgraph>=0.0.20,<0.3.0
langchain-openai>=0.0.2,<0.3.0
langchain-community>=0.0.10,<0.3.0
langchain-core>=0.1.0,<0.3.0
openai>=1.6.1,<2.0.0
ollama>=0.1.6,<1.0.0
gitpython>=3.1.40,<4.0.0
python-dotenv>=1.0.0,<2.0.0
tiktoken>=0.5.2,<1.0.0
mcp>=0.9.0,<1.0.0
```

# pyenv -- if pyenv is not already isntalled, please follow these steps
```
brew update
brew install pyenv
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init --path)"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc

# install the python version 3.13.1 and activate it
pyenv versions
pyenv install 3.13.1
pyenv global 3.13.1
python --version

pip install -r ./requirements.txt
pip install --upgrade pip
pip install -r ./requirements.txt
```

# ollama installation and running it as docker container
```
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
docker exec -it ollama ollama pull llama3.2
```

# .env
```
USE_OLLAMA=true
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434
```

# Run the code
```
python main.py
```
### This code will take a while if you execute it on your local Mac... Good luck and enjoy!