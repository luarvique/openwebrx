DATE=$(shell date +%F)
all:
	@docker build -t openwebrxplus-softmbe:$(DATE) -t openwebrxplus-softmbe .

run:
	@docker run --rm -h openwebrxplus-softmbe --name openwebrxplus-softmbe --device /dev/bus/usb -p 8073:8073 -v openwebrxplus-settings:/var/lib/openwebrx openwebrxplus-softmbe

admin:
	@docker exec -it openwebrxplus-softmbe /usr/bin/openwebrx admin adduser af

push:
	@docker tag openwebrxplus-softmbe:$(DATE) slechev/openwebrxplus-softmbe:$(DATE)
	@docker tag openwebrxplus-softmbe:$(DATE) slechev/openwebrxplus-softmbe:latest
	@docker push slechev/openwebrxplus-softmbe:$(DATE)
	@docker push slechev/openwebrxplus-softmbe

dev:
	@S6_CMD_ARG0=/bin/bash docker run -it --rm -p 8073:8073 --device /dev/bus/usb --name owrxp-build --entrypoint /bin/bash openwebrxplus-softmbe
