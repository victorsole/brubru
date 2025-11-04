<?php

use WPML\Element\API\Languages;
use WPML\FP\Obj;
use WPML\TM\API\ATE\CachedLanguageMappings;
use WPML\TM\API\Basket;
use WPML\TM\TranslationDashboard\FiltersStorage;
use WPML\TM\TranslationDashboard\SentContentMessages;
use WPML\Core\WP\App\Resources;
use WPML\UIPage;
use WPML\Media\Option;
use function WPML\Container\make;

/**
 * @author OnTheGo Systems
 */
class WPML_TM_Scripts_Factory {
	private $ate;
	private $auth;
	private $endpoints;
	private $strings;

	public function init_hooks() {
		add_action( 'admin_enqueue_scripts', array( $this, 'admin_enqueue_scripts' ) );
		add_filter( 'wpml_tm_translators_view_strings', array( $this, 'filter_translators_view_strings' ), 10, 2 );
	}

	/**
	 * @throws \InvalidArgumentException
	 */
	public function admin_enqueue_scripts() {
		$this->register_otgs_notices();

		wp_register_script(
			'ate-translation-editor-classic',
			WPML_TM_URL . '/dist/js/ate-translation-editor-classic/app.js',
			array( Resources::vendorAsDependency() ),
			ICL_SITEPRESS_SCRIPT_VERSION,
			true
		);

		if (
			WPML_TM_Page::is_tm_translators()
			|| UIPage::isTroubleshooting( $_GET )
		) {
			wp_enqueue_style( 'otgs-notices' );
			$this->localize_script( 'wpml-tm-settings' );
			wp_enqueue_script( 'wpml-tm-settings' );

			$this->create_ate()->init_hooks();
		}
		if ( WPML_TM_Page::is_settings() ) {
			wp_enqueue_style( 'otgs-notices' );
			$this->localize_script( 'wpml-settings-ui', [
				'shouldHandleMediaAuto' => Option::shouldHandleMediaAuto() ? "1" : "0",
			] );
			$this->create_ate()->init_hooks();
			wp_enqueue_script( 'wpml-tooltip' );
			wp_enqueue_style( 'wpml-tooltip' );
		}

		if ( WPML_TM_Page::is_translation_queue() && WPML_TM_ATE_Status::is_enabled() ) {
			$this->localize_script( 'ate-translation-queue' );
			wp_enqueue_script( 'ate-translation-queue' );
			wp_enqueue_script( 'ate-translation-editor-classic' );
			wp_enqueue_style( 'otgs-notices' );
		}

		if ( WPML_TM_Page::is_dashboard() ) {
			$this->load_notices_scripts_on_tm_dashboard();
		}

		if ( WPML_TM_Page::is_settings() ) {
			wp_enqueue_style(
				'wpml-tm-multilingual-content-setup',
				WPML_TM_URL . '/res/css/multilingual-content-setup.css',
				array(),
				ICL_SITEPRESS_SCRIPT_VERSION
			);
		}

		if ( WPML_TM_Page::is_notifications_page() ) {
			wp_enqueue_style(
				'wpml-tm-translation-notifications',
				WPML_TM_URL . '/res/css/translation-notifications.css',
				array(),
				ICL_SITEPRESS_SCRIPT_VERSION
			);
		}
	}

	private function load_notices_scripts_on_tm_dashboard() {
		// Since WPML 4.7, the old TM scripts are no longer needed.
		// However, we still need Ant Design framework and otgs-notices CSS for styling.

		// TODO:
		// - Refactor the dashboard CSS to remove these dependencies.
		// - Remove translationDashboard scripts once the WPML > TM > Jobs page migration is complete.
		wp_enqueue_style( 'otgs-notices' );
		$enqueueApp = Resources::enqueueApp( 'translationDashboard' );
		$enqueueApp();
	}

	public function register_otgs_notices() {
		if ( ! wp_style_is( 'otgs-notices', 'registered' ) ) {
			wp_register_style(
				'otgs-notices',
				ICL_PLUGIN_URL . '/res/css/otgs-notices.css',
				array( 'sitepress-style' )
			);
		}
	}

	/**
	 * @param $handle
	 *
	 * @throws \InvalidArgumentException
	 */
	public function localize_script( $handle, $additional_data = array() ) {
		wp_localize_script( $handle, 'WPML_TM_SETTINGS', $this->build_localize_script_data( $additional_data ) );
	}

	public function build_localize_script_data($additional_data = array()  ) {
		$data = array(
			'hasATEEnabled'      => WPML_TM_ATE_Status::is_enabled(),
			'restUrl'            => untrailingslashit( $this->getRestUrl() ),
			'restNonce'          => wp_create_nonce( 'wp_rest' ),
			'syncJobStatesNonce' => wp_create_nonce( 'sync-job-states' ),
			'ate'                => $this->create_ate()
			                        ->get_script_data(),
			'currentUser'   => null,
		);

		$data = array_merge( $data, $additional_data );

		$current_user = wp_get_current_user();
		if ( $current_user && $current_user->ID > 0 ) {
			$filtered_current_user      = clone $current_user;
			$filtered_current_user_data = new \stdClass();
			$blacklistedProps           = [ 'user_pass' ];

			foreach ( $current_user->data as $prop => $value ) {
				if ( in_array( $prop, $blacklistedProps ) ) {
					continue;
				}

				$filtered_current_user_data->$prop = $value;
			}
			$filtered_current_user->data = $filtered_current_user_data;

			$data['currentUser'] = $filtered_current_user;
		}

		return $data;
	}

	/**
	 * @return WPML_TM_MCS_ATE
	 * @throws \InvalidArgumentException
	 */
	public function create_ate() {
		if ( ! $this->ate ) {
			$this->ate = new WPML_TM_MCS_ATE(
				$this->get_authentication(),
				$this->get_endpoints(),
				$this->create_ate_strings()
			);
		}

		return $this->ate;
	}

	private function get_authentication() {
		if ( ! $this->auth ) {
			$this->auth = new WPML_TM_ATE_Authentication();
		}

		return $this->auth;
	}

	private function get_endpoints() {
		if ( ! $this->endpoints ) {
			$this->endpoints = WPML\Container\make( 'WPML_TM_ATE_AMS_Endpoints' );
		}

		return $this->endpoints;
	}

	private function create_ate_strings() {
		if ( ! $this->strings ) {
			$this->strings = new WPML_TM_MCS_ATE_Strings( $this->get_authentication(), $this->get_endpoints() );
		}

		return $this->strings;
	}

	/**
	 * @param array $strings
	 * @param bool  $all_users_have_subscription
	 *
	 * @return array
	 */
	public function filter_translators_view_strings( array $strings, $all_users_have_subscription ) {
		if ( WPML_TM_ATE_Status::is_enabled() ) {
			$strings['ate'] = $this->create_ate_strings()
								->get_status_HTML(
									$this->get_ate_activation_status(),
									$all_users_have_subscription
								);
		}

		return $strings;
	}

	/**
	 * @return string
	 */
	private function get_ate_activation_status() {
		$status = $this->create_ate_strings()
					   ->get_status();
		if ( $status !== WPML_TM_ATE_Authentication::AMS_STATUS_ACTIVE ) {
			$status = $this->fetch_and_update_ate_activation_status();
		}

		return $status;
	}

	/**
	 * @return string
	 */
	private function fetch_and_update_ate_activation_status() {
		$ams_api = WPML\Container\make( WPML_TM_AMS_API::class );
		$ams_api->get_status();

		return $this->create_ate_strings()
					->get_status();
	}

	/**
	 * @return string
	 */
	private function getRestUrl(): string {
		$restUrl = get_rest_url();
		if ( get_option( 'permalink_structure' ) === '' ) {
			$restUrl = add_query_arg( 'rest_route', '/', home_url( '/' ) );
		}
		return $restUrl;
	}
}
