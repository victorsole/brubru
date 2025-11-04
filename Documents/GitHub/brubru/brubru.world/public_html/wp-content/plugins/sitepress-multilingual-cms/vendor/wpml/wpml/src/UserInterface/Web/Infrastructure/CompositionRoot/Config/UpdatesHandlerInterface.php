<?php

namespace WPML\UserInterface\Web\Infrastructure\CompositionRoot\Config;

use WPML\UserInterface\Web\Infrastructure\CompositionRoot\Config\Updates\Update;

interface UpdatesHandlerInterface {


  /**
   * @param array<int, Update> $allUpdates
   * @return void
   */
  public function prepareUpdates( $allUpdates );


}
