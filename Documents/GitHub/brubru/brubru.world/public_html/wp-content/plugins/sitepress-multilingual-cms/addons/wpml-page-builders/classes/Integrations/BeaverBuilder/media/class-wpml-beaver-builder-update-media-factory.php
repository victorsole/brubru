<?php

class WPML_Beaver_Builder_Update_Media_Factory implements IWPML_PB_Media_Update_Factory {


	public function create( $find_usage_instead_of_translate = false ) {
		global $sitepress;

		$element_factory = new WPML_Translation_Element_Factory( $sitepress );
		if ( $find_usage_instead_of_translate ) {
			$media_translate = new WPML_Page_Builders_Media_Find_Usage();
		} else {
			$image_translate = new WPML_Media_Image_Translate(
				$sitepress,
				new WPML_Media_Attachment_By_URL_Factory(),
				new \WPML\Media\Factories\WPML_Media_Attachment_By_URL_Query_Factory()
			);
			$media_translate = new WPML_Page_Builders_Media_Translate( $element_factory, $image_translate );
		}

		return new WPML_Page_Builders_Update_Media(
			new WPML_Page_Builders_Update( new WPML_Beaver_Builder_Data_Settings_For_Media() ),
			new WPML_Translation_Element_Factory( $sitepress ),
			new WPML_Beaver_Builder_Media_Nodes_Iterator(
				new WPML_Beaver_Builder_Media_Node_Provider( $media_translate )
			),
			$find_usage_instead_of_translate
				? null
				: new WPML_Page_Builders_Media_Usage( $media_translate, new WPML_Media_Usage_Factory() )
		);
	}
}

