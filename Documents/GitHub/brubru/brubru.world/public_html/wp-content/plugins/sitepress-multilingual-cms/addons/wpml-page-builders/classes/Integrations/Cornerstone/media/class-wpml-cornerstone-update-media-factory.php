<?php

class WPML_Cornerstone_Update_Media_Factory extends WPML_Page_Builders_Media_Update_Factory {

	public function create( $find_usage_instead_of_translate = false ) {
		global $sitepress;
		return new WPML_Page_Builders_Update_Media(
			new WPML_Page_Builders_Update( new WPML_Cornerstone_Data_Settings() ),
			new WPML_Translation_Element_Factory( $sitepress ),
			new WPML_Cornerstone_Media_Nodes_Iterator(
				new WPML_Cornerstone_Media_Node_Provider( $this->get_media_translate( $find_usage_instead_of_translate ) )
			),
			$find_usage_instead_of_translate
				? null
				: new WPML_Page_Builders_Media_Usage( $this->get_media_translate( $find_usage_instead_of_translate ), new WPML_Media_Usage_Factory() )
		);
	}
}
