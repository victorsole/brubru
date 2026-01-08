<?php

/**
 * @author OnTheGo Systems
 */
class WPML_Download_Localization {
	private $active_languages;
	private $default_language;
	private $not_founds = array();
	private $errors     = array();

	/**
	 * WPML_Localization constructor.
	 *
	 * @param array  $active_languages
	 * @param string $default_language
	 */
	public function __construct( array $active_languages, $default_language ) {
		$this->active_languages = $active_languages;
		$this->default_language = $default_language;
	}

	public function download_language_packs() {
		$results = array();
		if ( $this->active_languages ) {
			if ( ! function_exists( 'request_filesystem_credentials' ) ) {
				/** WordPress Administration File API */
				require_once ABSPATH . 'wp-admin/includes/file.php';
			}

			$translation_install_file = get_home_path() . 'wp-admin/includes/translation-install.php';

			if ( ! file_exists( $translation_install_file ) ) {
				return array();
			}
			if ( ! function_exists( 'wp_can_install_language_pack' ) ) {
				/** WordPress Translation Install API */
				require_once $translation_install_file;
			}
			if ( ! function_exists( 'submit_button' ) ) {
				/** WordPress Administration File API */
				require_once ABSPATH . 'wp-admin/includes/template.php';
			}
			if ( ! wp_can_install_language_pack() ) {
				$this->errors[] = 'wp_can_install_language_pack';
			} else {
				foreach ( $this->active_languages as $active_language ) {
					$result = $this->download_language_pack( $active_language );
					if ( $result ) {
						$results[] = $result;
					}
				}
			}
		}

		$this->download_active_plugins_language_packs();

		return $results;
	}

	public function get_not_founds() {
		return $this->not_founds;
	}

	public function get_errors() {
		return $this->errors;
	}

	private function download_language_pack( $language ) {
		$result = null;

		if ( 'en_US' !== $language['default_locale'] ) {
			if ( $language['default_locale'] ) {
				$result = wp_download_language_pack( $language['default_locale'] );
			}
			if ( ! $result && $language['tag'] ) {
				$result = wp_download_language_pack( $language['tag'] );
			}
			if ( ! $result && $language['code'] ) {
				$result = wp_download_language_pack( $language['code'] );
			}

			if ( ! $result ) {
				$result             = null;
				$this->not_founds[] = $language;
			}
		}

		return $result;
	}

	public function download_active_plugins_language_packs() {
		$active_plugins = get_option( 'active_plugins' );
		if ( empty( $active_plugins ) ) {
			return;
		}

		foreach ( $active_plugins as $active_plugin ) {
			$this->download_plugin_translations( $active_plugin );
		}
	}

	/**
	 * @param string $plugin
	 * @return bool|WP_Error
	 */
	public function download_plugin_translations( string $plugin ) {
		if ( ! function_exists( 'get_plugin_data' ) ) {
			require_once ABSPATH . '/wp-admin/includes/plugin.php';
		}

		if ( ! function_exists( 'translations_api' ) ) {
			require_once ABSPATH . '/wp-admin/includes/translation-install.php';
		}

		if ( ! class_exists( 'Automatic_Upgrader_Skin' ) ) {
			require_once ABSPATH . '/wp-admin/includes/class-wp-upgrader.php';
		}

		$plugin_slug    = dirname( $plugin );
		$plugin_data    = get_plugin_data( WP_PLUGIN_DIR . '/' . $plugin, false, false );
		$plugin_version = $plugin_data['Version'];

		$api = translations_api(
			'plugins',
			[
				'slug'    => $plugin_slug,
				'version' => $plugin_version,
			]
		);

		if ( is_wp_error( $api ) ) {
			return $api;
		}

		if ( empty( $api['translations'] ) ) {
			// No translations.
			return true;
		}

		$toUpgrade = array();

		$locales = array_map(
			function ( $language ) {
				return $language['default_locale'];
			},
			$this->active_languages
		);

		foreach ( $api['translations'] as $translation ) {
			if (
				array_key_exists( 'language', $translation ) &&
				array_key_exists( 'package', $translation ) &&
				in_array( $translation['language'], $locales, true )
			) {
				$toUpgrade[] = (object) [
					'language' => $translation['language'],
					'type'     => 'plugin',
					'slug'     => $plugin_slug,
					'version'  => $plugin_version,
					'package'  => $translation['package'],
				];
			}
		}

		if ( empty( $toUpgrade ) ) {
			// No plugin translated languages correspond to $locales.
			return true;
		}

		$skin     = new Automatic_Upgrader_Skin();
		$upgrader = new Language_Pack_Upgrader( $skin );
		return $upgrader->bulk_upgrade( $toUpgrade );
	}
}
