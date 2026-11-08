# SPDX-License-Identifier: Apache-2.0
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/full_base_telephony.mk)
$(call inherit-product, vendor/omni/config/common.mk)
$(call inherit-product, device/oppo/OP486C/device.mk)

PRODUCT_DEVICE := OP486C
PRODUCT_NAME := omni_OP486C
PRODUCT_BRAND := OPPO
PRODUCT_MODEL := CPH1923
PRODUCT_MANUFACTURER := OPPO
