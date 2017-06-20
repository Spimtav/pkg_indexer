#Use the latest ubuntu base image and install python on top of it
FROM ubuntu
RUN apt-get update -yq && apt-get install -yqq python

#Set the work directory, and copy in the index scripts
WORKDIR /app
ADD indexer.py /app
ADD verbose_indexer.py /app

#Expose the server's listening port
EXPOSE 8080

#Run the server upon container launch
CMD ["python", "indexer.py", "--localhost"]
#CMD ["python", "verbose_indexer.py", "--localhost", "--debug"]
