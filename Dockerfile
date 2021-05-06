FROM odoo:13
ENV APP_PATH /venv
WORKDIR $APP_PATH
USER root
COPY requirements.txt /venv
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install -r requirements.txt