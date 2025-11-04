<?php

namespace WPML\WPSEO\Shared\Upgrade;

class CommandsProvider {

	/**
	 * @return \WPML\Collect\Support\Collection
	 */
	public static function get() {
		return wpml_collect(
			[
				Commands\DisableHeadLangs::class,
				Commands\TranslateExistingTermMeta::class,
			]
		);
	}

	/**
	 * @return string
	 */
	public static function getHash() {
		return md5( self::get()->implode( ',' ) );
	}
}
