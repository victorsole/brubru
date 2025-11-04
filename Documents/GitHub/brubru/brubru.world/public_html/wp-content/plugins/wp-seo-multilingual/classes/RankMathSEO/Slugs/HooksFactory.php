<?php

namespace WPML\WPSEO\RankMathSEO\Slugs;

class HooksFactory implements \IWPML_Backend_Action_Loader {

	/**
	 * @return \IWPML_Action|\IWPML_Action[]|callable|null
	 */
	public function create() {
		$slugTranslationSettingsFactory = class_exists( \WPML_ST_Slug_Translation_Settings_Factory::class )
			? new \WPML_ST_Slug_Translation_Settings_Factory()
			: null;

		if ( $slugTranslationSettingsFactory ) {
			return new Hooks( $slugTranslationSettingsFactory );
		}

		return null;
	}
}
