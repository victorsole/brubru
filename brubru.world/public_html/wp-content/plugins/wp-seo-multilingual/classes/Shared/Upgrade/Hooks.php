<?php

namespace WPML\WPSEO\Shared\Upgrade;

use WPML\Utilities\Lock;
use WPML\WPSEO\Shared\Options;

/**
 * Commands will run in admin only,
 * and below a lock to prevent concurrent upgrades.
 *
 * Changing the class name for a command or
 * adding a new command will re-trigger the whole
 * upgrade process.
 *
 * Each upgrade command is responsible for holding
 * its own status. If a command should not be re-triggered,
 * it should be defined inside the command class.
 */
class Hooks implements \IWPML_Backend_Action {

	const LOCK_NAME = 'wpml-seo-upgrade';

	const KEY_LAST_UPGRADE_HASH = 'last-upgrade-hash';

	public function add_hooks() {
		add_action( 'init', [ $this, 'init' ] );
	}

	/**
	 * @return void
	 */
	public function init() {
		if ( ! wp_doing_ajax() && $this->needsUpgrade() ) {
			Lock::whileLocked( self::LOCK_NAME, MINUTE_IN_SECONDS, [ $this, 'run' ] );
		}
	}

	/**
	 * @return bool
	 */
	private function needsUpgrade() {
		return Options::get( self::KEY_LAST_UPGRADE_HASH ) !== CommandsProvider::getHash();
	}

	public function run() {
		CommandsProvider::get()->each(
			function ( $commandClass ) {
				call_user_func( [ $commandClass, 'run' ] );
			}
		);

		Options::set( self::KEY_LAST_UPGRADE_HASH, CommandsProvider::getHash() );
	}
}
