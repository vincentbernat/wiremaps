# Convert all SVG to PNG

IMAGES=$(patsubst %.svg,%.png,$(wildcard *.svg))
WIDTH=747
MAXHEIGHT=320

all: $(IMAGES)

%.png: %.svg
	inkscape --file=$< --export-png=$@ -C \
		 --export-width=$(WIDTH)
	if [ $$(identify -format "%[fx:h]" $@) -gt $(MAXHEIGHT) ]; then \
		mogrify -resize $(WIDTH)x$(MAXHEIGHT) $@ ; \
	fi

clean:
	rm -f $(IMAGES)

.PHONY: clean
