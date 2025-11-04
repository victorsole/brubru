<?php

namespace WPML\UserInterface\Web\Infrastructure\CompositionRoot\Config\ContentStats;

use WPML\Core\Component\ReportContentStats\Application\Service\ContentStatsService;
use WPML\UserInterface\Web\Core\Port\Script\ScriptDataProviderInterface;
use WPML\UserInterface\Web\Core\Port\Script\ScriptPrerequisitesInterface;
use WPML\UserInterface\Web\Core\SharedKernel\Config\Endpoint\Endpoint;
use WPML\UserInterface\Web\Infrastructure\CompositionRoot\Config\ApiInterface;

class Controller implements
  ScriptPrerequisitesInterface,
  ScriptDataProviderInterface {

  /** @var Endpoint|null */
  private $endpoint;

  /** @var ApiInterface */
  private $api;

  /** @var ContentStatsService */
  private $contentStatsService;


  public function __construct(
    ApiInterface $api,
    ContentStatsService $contentStatsService
  ) {
    $this->api                 = $api;
    $this->contentStatsService = $contentStatsService;
  }


  public function scriptPrerequisitesMet(): bool {
    return $this->contentStatsService->canProcess();
  }


  public function jsWindowKey(): string {
    return 'wpmlContentStats';
  }


  public function initialScriptData(): array {
    return [
      'route' => $this->api->getFullUrl( $this->getEndpoint() ),
      'nonce' => $this->api->nonce(),
    ];
  }


  private function getEndpoint(): Endpoint {
    if ( $this->endpoint === null ) {
      $this->endpoint = new Endpoint( EndpointDataProvider::ID, EndpointDataProvider::PATH );
      $this->endpoint->setMethod( EndpointDataProvider::METHOD );
    }

    return $this->endpoint;
  }


}
