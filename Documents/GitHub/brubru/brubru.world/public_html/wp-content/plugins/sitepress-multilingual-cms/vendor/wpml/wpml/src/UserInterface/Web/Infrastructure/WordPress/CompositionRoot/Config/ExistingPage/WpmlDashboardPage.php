<?php

namespace WPML\UserInterface\Web\Infrastructure\WordPress\CompositionRoot\Config\ExistingPage;

use WPML\UserInterface\Web\Core\SharedKernel\Config\ExistingPageInterface;
use WPML\UserInterface\Web\Core\SharedKernel\Config\Notice;

class WpmlDashboardPage implements ExistingPageInterface {


  public function isActive() : bool {
    return ! empty( $GLOBALS['pagenow'] )
           && $GLOBALS['pagenow'] === 'admin.php'
           && ! empty( $_GET['page'] )
           && $_GET['page'] === 'tm/menu/main.php'
           && ( empty( $_GET['sm'] ) || $_GET['sm'] === 'dashboard' );
  }


  /**
   * @param Notice $notice
   *
   * @return void
   */
  public function renderNotice( Notice $notice ) {
    $notice->render();
  }


}
