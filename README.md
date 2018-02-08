# Sherlock at IMF

This project is a web-based system that creates index and search capabilities for the IMF Working papers.

# Downloads

1- Dataframe containing text and metadata for the working papers.
download and copy the file "scraped_meta_join_updated.pickle" into the root folder next to app.py

2- The index folder to enable search and retrieval.
download the file index.zip and extract the contents into the folder "index" into the root folder next to app.py

3- pdfs folder that contains all of the pdf files. 
download the file pdfs.zip and extract the contents into the folder "pdfs" into the "static" folder.

# Deployment
In order to deploy this project into a server you need 3 components installed on the server. 
1- python
2- nginx
3- virtualenv

On a linux machine use the following commands to install these components:

```
sudo apt-get update
sudo apt-get install python-pip python-dev nginx
sudo pip install virtualenv
```

# Create a Python Virtual Environment

```
virtualenv flask
source flask/bin/activate
pip install -r requirements.txt
```

# Setup reverse lookup

```
sudo vi /etc/nginx/sites-available/sherlock_at_imf
```

copy paste the following code into the file:

```
server {
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    location /static {
        alias  {{deployment path}}/search/static/;
    }
}
```

replace the {{deployment path}} with the address of the folder you cloned the repository into

# Running the server

Use the following command to run the server:

```
gunicorn app:app -b localhost:8000 --daemon
```



