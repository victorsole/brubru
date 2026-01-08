<?php

namespace WPML\Core\Component\MinimumRequirements\Domain\Entity;

use WPML\Core\SharedKernel\Component\Server\Domain\RestApiStatusInterface;

class RestEnabledRequirement extends RequirementBase {

  /**
   * @var RestApiStatusInterface
   */
  private $restApiStatus;


  /**
   * Constructor
   *
   * @param RestApiStatusInterface $restApiService
   */
  public function __construct( RestApiStatusInterface $restApiService ) {
    $this->restApiStatus = $restApiService;
  }


  public function getId(): int {
    return 4;
  }


  public function getTitle(): string {
    return __( 'WordPress REST API', 'wpml' );
  }


  public function getMessages(): array {
    $endpoint = $this->restApiStatus->getEndpoint();

    return [
      [
        'type'    => 'p',
        'message' => __(
          'The WordPress REST API must be enabled for WPML to work correctly.',
          'wpml'
        ),
      ],
      [
        'type'    => 'alert',
        'message' => sprintf(
          __(
            'Ensure the REST API endpoint %s '
            .
            'is reachable and that the WordPress REST API is enabled.',
            'wpml'
          ),
          '<strong>' . $endpoint . '</strong> '
        ),
      ]
    ];
  }


  protected function doIsValid(): bool {
    return $this->restApiStatus->isEnabled();
  }


  protected function getRequirementType(): string {
    return 'REST_API';
  }


}
