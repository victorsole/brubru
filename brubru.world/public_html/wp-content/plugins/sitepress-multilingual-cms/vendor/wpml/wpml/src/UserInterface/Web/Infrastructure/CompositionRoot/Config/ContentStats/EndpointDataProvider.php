<?php

namespace WPML\UserInterface\Web\Infrastructure\CompositionRoot\Config\ContentStats;

use WPML\UserInterface\Web\Core\Component\ContentStats\Application\Endpoint\CalculateContentStats\ProcessContentStatsController;
use WPML\UserInterface\Web\Core\SharedKernel\Config\Endpoint\MethodType;

class EndpointDataProvider {

  const ID = 'wpmlcontentstats';

  const PATH = '/wpml-content-stats';

  const HANDLER = ProcessContentStatsController::class;

  const METHOD = MethodType::POST;

}
