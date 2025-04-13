



local_deploy: clean
	cp -r addon $ANKI_ADDON_PATH


clean:
	rm -r $ANKI_ADDON_PATH
