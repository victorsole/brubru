<?php

namespace WPML\Legacy\SharedKernel\Installer\Application\Query;

use WPML\Core\SharedKernel\Component\Installer\Application\Query\WpmlSiteKeyQueryInterface;

class WpmlSiteKeyQuery implements WpmlSiteKeyQueryInterface {

  /** @var \WP_Installer|null */
  private $installer = null;


  public function __construct() {
    /**
     * We need to check for the class existence because.,
     * Installer is loaded in the function "wpml_installer_instance_delegator",
     * which is triggered after the hook "after_setup_theme".
     * This way is safer to avoid fatal errors that can happen when the class
     * is not loaded yet.
     */
    if ( class_exists( 'WP_Installer' ) ) {
      $this->installer = \WP_Installer::instance();
    }
  }


  /**
   * @return string|false
   */
  public function get() {
    if ( ! $this->installer ) {
      return false;
    }

    if ( ! $this->installer->get_repositories() ) {
      $this->installer->load_repositories_list();
    }

    if ( ! $this->installer->get_settings() ) {
      $this->installer->save_settings();
    }

    return $this->installer->get_repository_site_key( 'wpml' );
  }


}
