BUILD_DIR=target

TEMP_CONFIG_PATH=/tmp/anki_storytime__meta.json


build:
	mkdir ${BUILD_DIR}
	cp -r addon/* ${BUILD_DIR}
	cp -r ${LIB_DIR} ${BUILD_DIR}/libs


local_deploy:
	-mkdir ${ANKI_ADDON_PATH}
	cp -r ${BUILD_DIR}/* ${ANKI_ADDON_PATH}

local_deploy_clean: clean build local_deploy;


clean:
	-rm -rf ${BUILD_DIR}


clean_plugin_in_anki:
	-rm -rf ${ANKI_ADDON_PATH}




build-zip: clean build:
	cd ${BUILD_DIR}; zip -r ../anki_storytime.zip .	
