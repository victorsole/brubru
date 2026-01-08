// frontend/src/components/eu_comply/action_plan_timeline.tsx
import type { GapFinding } from '../../pages/eu_comply_page';
import './action_plan_timeline.css';

interface ActionPlanTimelineProps {
  gapFindings: GapFinding[];
}

interface GroupedAction {
  priority: number;
  findings: GapFinding[];
  totalCount: number;
}

export const ActionPlanTimeline = ({ gapFindings }: ActionPlanTimelineProps) => {
  const groupByPriority = (): GroupedAction[] => {
    const groups = new Map<number, GapFinding[]>();

    gapFindings.forEach(finding => {
      const priority = finding.priority || 5;
      if (!groups.has(priority)) {
        groups.set(priority, []);
      }
      groups.get(priority)!.push(finding);
    });

    // Sort findings within each group by deadline
    groups.forEach(findings => {
      findings.sort((a, b) => {
        if (!a.deadline_date) return 1;
        if (!b.deadline_date) return -1;
        return new Date(a.deadline_date).getTime() - new Date(b.deadline_date).getTime();
      });
    });

    // Convert to array and sort by priority (1 = highest)
    return Array.from(groups.entries())
      .map(([priority, findings]) => ({
        priority,
        findings,
        totalCount: findings.length,
      }))
      .sort((a, b) => a.priority - b.priority);
  };

  const getPriorityLabel = (priority: number): string => {
    switch (priority) {
      case 1: return 'Critical';
      case 2: return 'High';
      case 3: return 'Medium';
      case 4: return 'Low';
      case 5: return 'Optional';
      default: return 'Medium';
    }
  };

  const getPriorityColor = (priority: number): string => {
    switch (priority) {
      case 1: return 'priority-critical';
      case 2: return 'priority-high';
      case 3: return 'priority-medium';
      case 4: return 'priority-low';
      case 5: return 'priority-optional';
      default: return 'priority-medium';
    }
  };

  const getEffortIcon = (effort: string | undefined): string => {
    switch (effort?.toLowerCase()) {
      case 'quick': return 'mdi-clock-fast';
      case 'moderate': return 'mdi-clock-outline';
      case 'significant': return 'mdi-clock-alert-outline';
      default: return 'mdi-clock-outline';
    }
  };

  const isOverdue = (deadline?: string): boolean => {
    if (!deadline) return false;
    return new Date(deadline) < new Date();
  };

  const groupedActions = groupByPriority();

  if (gapFindings.length === 0) {
    return (
      <div className="action-plan-timeline">
        <div className="action-plan-timeline__header">
          <h2>
            <span className="mdi mdi-checkbox-multiple-marked-outline"></span>
            Action Plan
          </h2>
        </div>
        <div className="action-plan-timeline__empty">
          <span className="mdi mdi-check-all"></span>
          <p>All requirements met! No action items needed.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="action-plan-timeline">
      <div className="action-plan-timeline__header">
        <h2>
          <span className="mdi mdi-format-list-checkbox"></span>
          Action Plan
        </h2>
        <div className="action-plan-timeline__summary">
          {gapFindings.length} action {gapFindings.length === 1 ? 'item' : 'items'} requiring attention
        </div>
      </div>

      <div className="action-plan-timeline__groups">
        {groupedActions.map(group => (
          <div key={group.priority} className={`action-plan-timeline__group ${getPriorityColor(group.priority)}`}>
            <div className="action-plan-timeline__group-header">
              <div className="action-plan-timeline__group-title">
                <span className="action-plan-timeline__priority-badge">
                  Priority {group.priority}
                </span>
                <span className="action-plan-timeline__priority-label">
                  {getPriorityLabel(group.priority)}
                </span>
                <span className="action-plan-timeline__group-count">
                  ({group.totalCount} {group.totalCount === 1 ? 'item' : 'items'})
                </span>
              </div>
            </div>

            <div className="action-plan-timeline__items">
              {group.findings.map(finding => (
                <div key={finding.id} className="action-plan-timeline__item">
                  <div className="action-plan-timeline__item-header">
                    <div className="action-plan-timeline__item-title">
                      <span className="action-plan-timeline__item-article">
                        {finding.article_number}
                      </span>
                      {finding.deadline_date && (
                        <span className={`action-plan-timeline__item-deadline ${isOverdue(finding.deadline_date) ? 'overdue' : ''}`}>
                          <span className="mdi mdi-calendar-clock"></span>
                          {isOverdue(finding.deadline_date) ? 'Overdue: ' : 'Due: '}
                          {new Date(finding.deadline_date).toLocaleDateString()}
                        </span>
                      )}
                      {finding.estimated_effort && (
                        <span className="action-plan-timeline__item-effort">
                          <span className={`mdi ${getEffortIcon(finding.estimated_effort)}`}></span>
                          {finding.estimated_effort}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="action-plan-timeline__item-requirement">
                    {finding.requirement_text}
                  </div>

                  {finding.recommendation && (
                    <div className="action-plan-timeline__item-recommendation">
                      <span className="mdi mdi-lightbulb-on-outline"></span>
                      <strong>Action:</strong> {finding.recommendation}
                    </div>
                  )}

                  {finding.gap_description && (
                    <div className="action-plan-timeline__item-gap">
                      <span className="mdi mdi-alert-circle-outline"></span>
                      <strong>What's missing:</strong> {finding.gap_description}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="action-plan-timeline__legend">
        <h3>Priority Guide:</h3>
        <ul>
          <li>
            <span className="action-plan-timeline__legend-badge priority-critical">1</span>
            <strong>Critical:</strong> Immediate action required, significant legal risk
          </li>
          <li>
            <span className="action-plan-timeline__legend-badge priority-high">2</span>
            <strong>High:</strong> Important compliance requirement, address soon
          </li>
          <li>
            <span className="action-plan-timeline__legend-badge priority-medium">3</span>
            <strong>Medium:</strong> Standard compliance, plan implementation
          </li>
          <li>
            <span className="action-plan-timeline__legend-badge priority-low">4</span>
            <strong>Low:</strong> Minor gaps, address when possible
          </li>
          <li>
            <span className="action-plan-timeline__legend-badge priority-optional">5</span>
            <strong>Optional:</strong> Recommended best practices
          </li>
        </ul>
      </div>
    </div>
  );
};
