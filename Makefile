BUILD_DIR=target

ZIP_FILE=anki_storytime.zip


build: 
	-mkdir ${BUILD_DIR}
	-mkdir ${BULID_DIR}/libs
	cp -r addon/* ${BUILD_DIR}
	python3 -m pip install -r requirements.txt --target ${BUILD_DIR}/libs
	find ${BUILD_DIR} -name '__pycache__' -type d -prune -exec rm -r "{}" \;
	find ${BUILD_DIR} -name '*.pyc' -delete

local-deploy: build
	-mkdir ${ANKI_ADDON_PATH}
	cp -r ${BUILD_DIR}/* ${ANKI_ADDON_PATH}

build-deployable-zip: build
	cd ${BUILD_DIR}; zip -r ../${ZIP_FILE} .

clean:
	-rm -rf ${BUILD_DIR}
	-rm -rf ${ZIP_FILE}

clean-plugin-in-anki:
	-rm -rf ${ANKI_ADDON_PATH}


