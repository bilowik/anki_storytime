BUILD_DIR=target



build:
	mkdir ${BUILD_DIR}
	cp -r addon/* ${BUILD_DIR}
	cp -r ${LIB_DIR} ${BUILD_DIR}/libs


local_deploy:
	cp -r ${BUILD_DIR} ${ANKI_ADDON_PATH}

local_deploy_clean: clean build local_deploy;


clean:
	-rm -rf ${ANKI_ADDON_PATH}
	-rm -rf ${BUILD_DIR}
