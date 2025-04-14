BUILD_DIR=target

TEMP_CONFIG_PATH=/tmp/anki_storytime__meta.json

ZIP_FILE=anki_storytime.zip


initialize-build-dir:
	mkdir ${BUILD_DIR}

copy-code:
	cp -r addon/* ${BUILD_DIR}

local-quick-build: initialize_build_dir copy-code
	cp -r ${LIB_DIR} ${BUILD_DIR}/libs


local-deploy:
	-mkdir ${ANKI_ADDON_PATH}
	cp -r ${BUILD_DIR}/* ${ANKI_ADDON_PATH}

local-deploy-clean: clean local-quick-build local_deploy;


clean:
	-rm -rf ${BUILD_DIR}
	-rm -rf ${ZIP_FILE}


clean-plugin-in-anki:
	-rm -rf ${ANKI_ADDON_PATH}




build-deployable-zip: clean initialize-build-dir copy-code;
	mkdir ${BUILD_DIR}/libs
	python3 -m pip install -r requirements.txt --target ${BUILD_DIR}/libs
	find ${BUILD_DIR} -name '__pycache__' -type d -prune -exec rm -r "{}" \;
	find ${BUILD_DIR} -name '*.pyc' -delete
	cd ${BUILD_DIR}; zip -r ../${ZIP_FILE} .
