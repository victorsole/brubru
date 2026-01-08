<?php

namespace WPML\MinimumRequirements;

use IWPML_Backend_Action;
use Throwable;
use WPML\Core\Component\MinimumRequirements\Application\Service\RequirementsService;
use WPML\LIB\WP\Hooks;
use WPML\LIB\WP\User;
use WPML_Notice;

use function WPML\PHP\Logger\error;

/**
 * Class Display_Notice_Minimum_Requirements_If_Needed
 *
 * Handles the display of admin notices and in status bar when minimum system requirements are not met.
 * This class is responsible for generating and displaying warning notifications
 * through WordPress admin_notices hook when the plugin's requirements are not satisfied.
 * It is also responsible for loading the data needed to show the requirements notice in the status bar.
 */
class Display_Notice_Minimum_Requirements_If_Needed implements IWPML_Backend_Action {
	/**
	 * Allowed screens for displaying the requirements notice as Admin Notice.
	 * The notice wil always be displayed in the status bar.
	 */
	const ALLOWED_SCREENS
		= array(
			'edit-post',
			'term',
			'toplevel_page_tm/menu/main',
			'sitepress-multilingual-cms/menu/languages',
			'sitepress-multilingual-cms/menu/theme-localization',
			'wpml_page_tm/menu/translations-queue',
			'sitepress-multilingual-cms/menu/menu-sync/menus-sync',
			'wpml_page_sitepress-multilingual-cms/menu/taxonomy-translation',
			'wpml_page_tm/menu/settings',
			'wpml-string-translation/menu/string-translation',
			'wpml_page_wpml-package-management',
		);

	const NOTICE_GROUP = 'wpml-requirements';
	const NOTICE_ID = 'wpml-requirements-notice';
	const SUCCESS_NOTICE_ID = 'wpml-requirements-met-notice';


	public function __construct() {
	}


	/**
	 * Register hooks for the notification
	 */
	public function add_hooks() {
		Hooks::onAction( 'current_screen' )
		     ->then( [ $this, 'retrieve_invalid_requirements' ] )
		     ->then( [ $this, 'load_statusbar_notification_data' ] )
		     ->then( [ $this, 'display_wordpress_notice_if_needed' ] );
	}


	public function retrieve_invalid_requirements( $screens ) {
		global $wpml_dic;
		try {
			$requirements_service = $wpml_dic->make( RequirementsService::class );
			$useCache             = $this->userIsVisitingSupportPage( $screens[0] );

			return $requirements_service->getInvalidRequirements( $useCache );
		} catch ( Throwable $e ) {
			error( 'Failed to get InvalidRequirements: ' . $e->getMessage() . ' ' . $e->getTraceAsString() );

			return [];
		}
	}

	/**
	 * Check if there are invalid requirements and add a notice if needed
	 */
	public function display_wordpress_notice_if_needed( $invalid_requirements ) {
		try {
			if ( empty( $invalid_requirements ) ) {
				$isRemoved = $this->remove_requirements_are_not_met_notice_if_exists();
				if ( $isRemoved ) {
					$this->display_requirements_met_success_notice();
				}
			} else {
				$this->display_requirements_are_not_met_notice();
			}
		} catch ( Throwable $e ) {
			error( 'Failed to get InvalidRequirements: ' . $e->getMessage() . ' ' . $e->getTraceAsString() );
		}
	}

	/**
	 * The scope of this function is to load the data needed to show the requirements notice
	 * in the status bar that we have in the top bar.
	 *
	 * @param $minimumRequirements
	 *
	 * @return array
	 */
	public function load_statusbar_notification_data( $minimumRequirements ) {
		wp_localize_script(
			'wpml-ate-jobs-sync-ui', // Inject the data when the script that render the component <StatusBar> is preloaded.
			'wpmlMinimumRequirements',
			[
				'supportPageUrl' => admin_url( 'admin.php?page=sitepress-multilingual-cms/menu/support.php' ),
				'items'          => $minimumRequirements,
			]
		);

		return $minimumRequirements;
	}


	/**
	 * Add the notice to the admin notices system
	 */
	private function display_requirements_are_not_met_notice() {
		$admin_notices = wpml_get_admin_notices();

		$notice = new WPML_Notice(
			self::NOTICE_ID,
			$this->get_requirements_are_not_met_text(),
			self::NOTICE_GROUP
		);

		$notice->set_css_class_types( [ 'warning' ] );
		$notice->add_capability_check( [ 'manage_options' ] );
		$notice->set_dismissible( true );

		$notice->add_user_restriction( User::getCurrentId() );
		$notice->set_restrict_to_screen_ids( self::ALLOWED_SCREENS );

		$admin_notices->add_notice( $notice );
	}

	/**
	 * Generate the notice text
	 *
	 * @return string
	 */
	private function get_requirements_are_not_met_text() {
		$support_url = esc_url( admin_url( 'admin.php?page=sitepress-multilingual-cms/menu/support.php' ) );
		$message     = __( 'Your site doesn\'t meet WPML\'s minimum requirements.', 'sitepress' );
		$button_text = __( 'Fix now', 'sitepress' );

		$notice_text = <<<HTML
<div style="display: flex; align-items: center;" data-testid="wpml-minimum-requirements-notice">
    <span>{$message}</span>
    <a href="{$support_url}" style="margin-left: 15px;
	     background-color: #373737; color: white; text-decoration: none;
	     padding: 5px 10px; border-radius: 3px;">{$button_text}
    </a>
</div>
HTML;

		return $notice_text;
	}

	private function get_all_requirements_are_met_notice() {
		$message = __( 'Great! All WPML requirements are now met. Your site is ready to use WPML.', 'sitepress' );

		$notice_text = <<<HTML
<div style="display: flex; align-items: center;min-height:32px;" data-testid="wpml-minimum-requirements-are-met">
    <span>{$message}</span>
</div>
HTML;

		return $notice_text;
	}

	/**
	 * Display a success notice when all requirements are met (only once)
	 */
	private function display_requirements_met_success_notice() {
		$admin_notices = wpml_get_admin_notices();

		$notice = new WPML_Notice(
			self::SUCCESS_NOTICE_ID,
			$this->get_all_requirements_are_met_notice(),
			self::NOTICE_GROUP
		);

		$notice->set_css_class_types( [ 'success' ] );
		$notice->add_capability_check( [ 'manage_options' ] );
		$notice->set_dismissible( true );
		$notice->add_user_restriction( User::getCurrentId() );
		$notice->set_flash( true ); // This makes the notice show only once

		$admin_notices->add_notice( $notice );
	}

	private function remove_requirements_are_not_met_notice_if_exists() {
		$service = wpml_get_admin_notices();

		$notice = $service->get_notice( self::NOTICE_ID, self::NOTICE_GROUP );
		if ( ! $notice ) {
			return false;
		}

		$service->undismiss_notice( $notice );
		$service->remove_notice( $notice->get_group(), $notice->get_id() );

		return true;
	}

	/**
	 * @param $screen
	 *
	 * @return bool
	 */
	private function userIsVisitingSupportPage( $screen ): bool {
		return $screen && $screen->id !== 'sitepress-multilingual-cms/menu/support';
	}
}
