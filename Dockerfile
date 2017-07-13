FROM docker:17.05.0-ce

WORKDIR /app
COPY . /app

RUN apk update \
    # apk upgrade && \
    && apk add --no-cache bash git openssh postgresql python3 \
    && apk add --no-cache --virtual build-dependencies build-base gcc make musl-dev postgresql-dev python3-dev \
    && echo "### INSTALL PYTHON3/PIP3" \
    && python3 -m ensurepip \
    && rm -r /usr/lib/python*/ensurepip \
    && pip3 install --upgrade pip setuptools \
    && if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi \
    && echo "### INSTALL PIP REQUIREMENTS" \
    && pip install -r requirements.txt \
    && echo "### INSTALL GIT EXTRAS" \
    && git clone https://github.com/tj/git-extras.git \
    && cd git-extras \
    && git checkout $(git describe --tags $(git rev-list --tags --max-count=1)) &> /dev/null \
    && make install \
    && cd ../ \
    && rm -rf git-extras \
    && echo "### CLEAN UP" \
    && apk del build-dependencies \
    && rm -r /root/.cache

# ./run looks for docker group even though we are root
COPY ./groups-wrapper /usr/local/bin/groups
RUN chmod +x /usr/local/bin/groups
