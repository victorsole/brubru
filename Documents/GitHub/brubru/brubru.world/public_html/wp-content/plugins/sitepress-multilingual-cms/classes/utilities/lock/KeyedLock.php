<?php

namespace WPML\Utilities;

class KeyedLock extends Lock {

	/** @var string $keyName */
	private $keyName;

	/**
	 * Lock constructor.
	 *
	 * @param \wpdb  $wpdb
	 * @param string $name
	 */
	public function __construct( \wpdb $wpdb, $name ) {
		$this->keyName = 'wpml.' . $name . '.lock.key';
		parent::__construct( $wpdb, $name );
	}

	/**
	 * @param string|null $key
	 * @param int|null    $release_timeout
	 *
	 * @return string|false The key or false if could not acquire the lock
	 */
	public function create( $key = null, $release_timeout = null ) {
		$acquired = parent::create( $release_timeout );

		if ( $acquired ) {

			if ( ! $key ) {
				$key = wp_generate_uuid4();
			}

			$this->maybePurgeInvalidCache();
			update_option( $this->keyName, $key, false ); // this option should not be autoloaded due to the concurrency issue

			return $key;
		} elseif ( $key === get_option( $this->keyName ) ) {
			$this->extendTimeout();

			return $key;
		}

		return false;
	}

	public function release() {
		delete_option( $this->keyName );
		// When running concurrent calls to delete_option, the cache might not be updated properly.
		// And WP will skip its own cache invalidation.
		wp_cache_delete( $this->keyName, 'options' );

		return parent::release();
	}

	private function extendTimeout() {
		update_option( $this->name, time(), false );
	}

	/**
	 * Previously, we faced a problem with invalid cache that didn't accurately mirror the database state.
	 * This issue could arise from concurrent requests deleting WP_Options.
	 * The function now addresses such issues dynamically if they occur on a customer site.
	 * However, in the latest code version, this problem should no longer happen.
	 * The function is designed to resolve issues that existed prior to this fix being implemented.
	 *
	 * @see wpmldev-5396
	 */
	private function maybePurgeInvalidCache() {
		$alloptions = wp_cache_get( 'alloptions', 'options', true );
		if ( is_array( $alloptions ) && isset( $alloptions[ $this->keyName ] ) ) {
			wp_cache_delete( 'alloptions', 'options' );
		}
	}
}
