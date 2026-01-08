<?php

namespace WPML\UserInterface\Web\Core\Component\ATE\Application\Endpoint\GetWebsiteContext;

use WPML\Core\Component\ATE\Application\Query\WebsiteContextException;
use WPML\Core\Component\ATE\Application\Query\WebsiteContextQueryInterface;
use WPML\Core\Port\Endpoint\EndpointInterface;

class GetWebsiteContextController implements EndpointInterface {

  /** @var WebsiteContextQueryInterface */
  private $websiteContext;


  public function __construct( WebsiteContextQueryInterface $websiteContext ) {
    $this->websiteContext = $websiteContext;
  }


  /**
   * @param array<string,mixed> $requestData
   *
   * @return array<string, mixed>
   */
  public function handle( $requestData = null ): array {
    try {
      return [
        'success' => true,
        'data'    =>  $this->websiteContext
            ->getWebsiteContext()
            ->jsonSerialize()
      ];
    } catch ( WebsiteContextException $e ) {
      return [
        'success' => false,
        'message' => $e->getMessage(),
      ];
    }
  }


}
