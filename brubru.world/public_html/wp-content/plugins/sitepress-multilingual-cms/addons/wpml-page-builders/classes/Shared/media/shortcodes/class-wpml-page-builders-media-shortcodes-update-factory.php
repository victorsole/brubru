<?php

class WPML_Page_Builders_Media_Shortcodes_Update_Factory extends WPML_Page_Builders_Media_Update_Factory {

	/** @var WPML_PB_Config_Import_Shortcode WPML_PB_Config_Import_Shortcode */
	private $page_builder_config_import;

	/** @var WPML_Translation_Element_Factory|null $element_factory */
	private $element_factory;

	public function __construct( WPML_PB_Config_Import_Shortcode $page_builder_config_import ) {
		$this->page_builder_config_import = $page_builder_config_import;
	}

	public function create( $find_usage_instead_of_translate = false ) {
		$media_shortcodes = new WPML_Page_Builders_Media_Shortcodes(
			$this->get_media_translate( $find_usage_instead_of_translate ),
			$this->page_builder_config_import->get_media_settings()
		);

		return new WPML_Page_Builders_Media_Shortcodes_Update(
			$this->get_element_factory(),
			$media_shortcodes,
			$find_usage_instead_of_translate
				? null
				: new WPML_Page_Builders_Media_Usage( $this->get_media_translate( $find_usage_instead_of_translate ), new WPML_Media_Usage_Factory() )
		);
	}

	/** @return WPML_Translation_Element_Factory */
	private function get_element_factory() {
		global $sitepress;

		if ( ! $this->element_factory ) {
			$this->element_factory = new WPML_Translation_Element_Factory( $sitepress );
		}

		return $this->element_factory;
	}
}
