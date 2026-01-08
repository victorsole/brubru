<?php

abstract class WPML_Page_Builders_Media_Update_Factory implements IWPML_PB_Media_Update_Factory {

	/**
	 * @param boolean $find_usage_instead_of_translate
	 *
	 * @return IWPML_PB_Media_Find_And_Translate
	 */
	protected function get_media_translate( $find_usage_instead_of_translate ) {
		global $sitepress;

		$element_factory = new WPML_Translation_Element_Factory( $sitepress );
		if ( $find_usage_instead_of_translate ) {
			return new WPML_Page_Builders_Media_Find_Usage();
		}

		$image_translate = new WPML_Media_Image_Translate(
			$sitepress,
			new WPML_Media_Attachment_By_URL_Factory(),
			new \WPML\Media\Factories\WPML_Media_Attachment_By_URL_Query_Factory()
		);

		return new WPML_Page_Builders_Media_Translate( $element_factory, $image_translate );
	}
}
