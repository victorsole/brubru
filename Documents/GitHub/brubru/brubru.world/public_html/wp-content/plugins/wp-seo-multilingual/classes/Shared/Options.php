<?php

namespace WPML\WPSEO\Shared;

use WPML\WP\OptionManager;

class Options {

	const GROUP = 'wpml-seo';

	/**
	 * @param string $key
	 * @param mixed  $defaultValue
	 *
	 * @return mixed
	 */
	public static function get( $key, $defaultValue = null ) {
		return ( new OptionManager() )->get( self::GROUP, $key, $defaultValue );
	}

	/**
	 * @param string $key
	 * @param mixed  $value
	 *
	 * @return void
	 */
	public static function set( $key, $value ) {
		( new OptionManager() )->set( self::GROUP, $key, $value );
	}
}
