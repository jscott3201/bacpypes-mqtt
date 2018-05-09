FROM python:3.6
ADD . /bacnet
WORKDIR /bacnet
RUN pip install -r requirements.txt
CMD ["python", "rpm.py"]
EXPOSE 47808/udp
EXPOSE 8883