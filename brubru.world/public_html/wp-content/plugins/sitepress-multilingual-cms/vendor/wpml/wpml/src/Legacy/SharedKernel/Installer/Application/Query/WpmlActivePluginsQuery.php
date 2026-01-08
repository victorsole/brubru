<?php

namespace WPML\Legacy\SharedKernel\Installer\Application\Query;

use WPML\Core\SharedKernel\Component\Installer\Application\Query\WpmlActivePluginsQueryInterface;

class WpmlActivePluginsQuery implements WpmlActivePluginsQueryInterface {

  /** @var \WP_Installer */
  private $installer;

  /** @var \OTGS_Installer_Factory|null */
  private $installerFactory = null;


  public function __construct() {
    /**
     * We need to check for the class existence because.,
     * Installer is loaded in the function "wpml_installer_instance_delegator",
     * which is triggered after the hook "after_setup_theme".
     * This way is safer to avoid fatal errors that can happen when the class
     * is not loaded yet.
     */
    $this->installer = class_exists( 'WP_Installer' ) ?
      \WP_Installer::instance() :
      null;

    if ( $this->installer && class_exists( 'OTGS_Installer_Factory' ) ) {
      $this->installerFactory = new \OTGS_Installer_Factory( $this->installer );
    }
  }


  /**
   * @return array<int, array{
   *    id: string,
   *    slug: string,
   *    name: string,
   *    active: bool,
   *   current_version: string,
   *   installed_version: string,
   *  }>
   */
  public function getActivePlugins(): array {
    if ( ! $this->installerFactory ) {
      return [];
    }

    /**
     * @var array<string, array<int, array{
     *   id: string,
     *   slug: string,
     *   name: string,
     *   active: bool,
     *   current_version: string,
     *   installed_version: string,
     * }>> $plugins
     */
    $plugins = $this
        ->installerFactory
        ->get_plugin_finder()
        ->getOTGSInstalledPluginsByRepository( true, true );

    $wpmlPlugins = $plugins['wpml'] ?? [];

    return array_filter(
      $wpmlPlugins,
      function ( $wpmlPlugin ) {
        return $wpmlPlugin['active'];
      }
    );
  }


}
