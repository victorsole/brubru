<?php

namespace WPML\UserInterface\Web\Core\Component\MinimumRequirements\Application\EndPoint\MinimumRequirements;

use Throwable;
use WPML\Core\Component\MinimumRequirements\Application\Service\RequirementsService;
use WPML\Core\Port\Endpoint\EndpointInterface;

use function WPML\PHP\Logger\error;

class GetRequirementsController implements EndpointInterface {

  /** @var RequirementsService */
  private $service;


  public function __construct( RequirementsService $service ) {
    $this->service = $service;
  }


  /**
   * @param array<string,mixed>|null $requestData
   *
   * @return array<mixed, mixed>
   */
  public function handle( $requestData = null ): array {
    try {
      $useCache                = $this->getBooleanInput( $requestData, 'useCache', false );
      $onlyInvalidRequirements = $this->getBooleanInput( $requestData, 'onlyInvalidRequirements', false );

      if ( $onlyInvalidRequirements ) {
        $requirements = $this->service->getInvalidRequirements( $useCache );
      } else {
        $requirements = $this->service->getAllRequirements( $useCache );
      }

      return [
        'success' => true,
        'data'    => $requirements
      ];
    } catch ( Throwable $e ) {
      error(
        'Error validating requirement: ' . $e->getMessage() . ' | File: '
        . $e->getFile() . ' | Line: ' . $e->getLine() . ' | Trace: '
        . $e->getTraceAsString()
      );

      return [
        'success' => false,
        'message' => $e->getMessage()
      ];
    }
  }


  /**
   * Gets a boolean parameter from request data with a default value
   *
   * @param array<string,mixed>|null $requestData
   * @param string                   $paramName
   * @param bool                     $default
   *
   * @return bool
   */
  private function getBooleanInput(
    $requestData, string $paramName, bool $default = false
  ): bool {
    if ( ! is_array( $requestData ) || ! isset( $requestData[ $paramName ] ) ) {
      return $default;
    }

    return filter_var(
      $requestData[ $paramName ],
      FILTER_VALIDATE_BOOLEAN
    );
  }


}
