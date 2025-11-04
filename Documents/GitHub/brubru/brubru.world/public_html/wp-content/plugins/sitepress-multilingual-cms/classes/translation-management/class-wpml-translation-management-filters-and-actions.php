<?php

class WPML_Translation_Management_Filters_And_Actions {
	/**
	 * @var  SitePress $sitepress
	 */
	private $sitepress;
	/**
	 * @var \AbsoluteLinks
	 */
	private $absolute_links;
	/**
	 * @var \WPML_Absolute_To_Permalinks
	 */
	private $permalinks_converter;
	/**
	 * @var \WPML_Translate_Link_Targets_In_Custom_Fields
	 */
	private $translate_links_in_custom_fields;
	/**
	 * @var \WPML_Translate_Link_Targets_In_Custom_Fields_Hooks
	 */
	private $translate_links_in_custom_fields_hooks;
	/**
	 * @var \WPML_Translate_Link_Targets
	 */
	private $translate_link_target;
	/**
	 * @var \WPML_Translate_Link_Targets_Hooks
	 */
	private $translate_link_target_hooks;

	/**
	 * @param TranslationManagement $tm_instance
	 * @param \SitePress            $sitepress
	 */
	public function __construct( $tm_instance, $sitepress ) {
		$this->sitepress = $sitepress;
		$wp_api          = $this->sitepress->get_wp_api();

		if ( ! is_admin() ) {
			$this->add_filters_for_translating_link_targets( $tm_instance, $wp_api );
			$this->addFiltersForTranslatingIdsInCustomFields( $tm_instance, $wp_api );
		}

	}

	private function add_filters_for_translating_link_targets( &$tm_instance, &$wp_api ) {
		$this->absolute_links                         = new AbsoluteLinks();
		$this->permalinks_converter                   = new WPML_Absolute_To_Permalinks( $this->sitepress );
		$this->translate_links_in_custom_fields       = new WPML_Translate_Link_Targets_In_Custom_Fields(
			$tm_instance,
			$wp_api,
			$this->absolute_links,
			$this->permalinks_converter
		);
		$this->translate_links_in_custom_fields_hooks = new WPML_Translate_Link_Targets_In_Custom_Fields_Hooks(
			$this->translate_links_in_custom_fields,
			$wp_api
		);

		$this->translate_link_target       = new WPML_Translate_Link_Targets( $this->absolute_links, $this->permalinks_converter );
		$this->translate_link_target_hooks = new WPML_Translate_Link_Targets_Hooks( $this->translate_link_target, $wp_api );
	}

	private function addFiltersForTranslatingIdsInCustomFields( &$tmInstance, &$wpApi ) {
		$translateNestedIds = new \WPML\Utils\TranslateNestedIds( $this->sitepress );

		new \WPML\CustomFieldTranslation\TranslateIdsInPostCustomFieldsHooks(
			new \WPML\CustomFieldTranslation\TranslateIdsInPostCustomFields(
				$tmInstance,
				$wpApi,
				$translateNestedIds
			),
			$wpApi
		);

		new \WPML\CustomFieldTranslation\TranslateIdsInTermCustomFieldsHooks(
			new \WPML\CustomFieldTranslation\TranslateIdsInTermCustomFields(
				$tmInstance,
				$wpApi,
				$translateNestedIds
			),
			$wpApi
		);
	}

}
