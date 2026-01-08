<?php

class WPML_Elementor_Update_Media_Factory implements IWPML_PB_Media_Update_Factory {

	public function create( $find_usage_instead_of_translate = false ) {
		global $sitepress;

		return new WPML_Page_Builders_Update_Media(
			new WPML_Page_Builders_Update( new WPML_Elementor_Data_Settings() ),
			new WPML_Translation_Element_Factory( $sitepress ),
			new WPML_Elementor_Media_Nodes_Iterator(
				new WPML_Elementor_Media_Node_Provider( $this->get_media_translate( $find_usage_instead_of_translate ) )
			),
			$find_usage_instead_of_translate
				? null
				: new WPML_Page_Builders_Media_Usage( $this->get_media_translate( $find_usage_instead_of_translate ), new WPML_Media_Usage_Factory() )
		);
	}

	/**
	 * @param boolean $find_usage_instead_of_translate
	 *
	 * @return IWPML_PB_Media_Find_And_Translate
	 */
	private function get_media_translate( $find_usage_instead_of_translate ) {
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
