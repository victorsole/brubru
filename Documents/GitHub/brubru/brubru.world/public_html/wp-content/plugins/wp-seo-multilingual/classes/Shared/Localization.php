<?php

namespace WPML\WPSEO\Shared;

class Localization implements \IWPML_Backend_Action, \IWPML_Frontend_Action {

	public function add_hooks() {
		add_action( 'init', [ $this, 'init' ] );
	}

	public function init() {
		load_plugin_textdomain( 'wp-seo-multilingual', false, basename( __DIR__ ) . '/languages' );
	}
}
