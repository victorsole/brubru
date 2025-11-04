<?php

namespace WPML\Core\Component\ATE\Application\Query;

use WPML\Core\Component\ATE\Application\Query\Dto\WebsiteContextDto;

interface WebsiteContextQueryInterface {


  /**
   * @return WebsiteContextDto
   * @throws WebsiteContextException
   */
  public function getWebsiteContext(): WebsiteContextDto;


  public function isContextPresent(): bool;


}
