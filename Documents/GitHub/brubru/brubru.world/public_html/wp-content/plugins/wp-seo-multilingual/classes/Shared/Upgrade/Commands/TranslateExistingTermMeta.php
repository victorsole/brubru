<?php
namespace WPML\WPSEO\Shared\Upgrade\Commands;

class TranslateExistingTermMeta implements Command {

	const OPTION = 'wpseo_taxonomy_meta';

	public static function run() {
		if ( defined( 'WPSEO_VERSION' ) ) {
			do_action( 'update_option', self::OPTION, false, get_option( self::OPTION ) );
		}
	}
}
