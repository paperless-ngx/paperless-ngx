import { ChangeDetectionStrategy, Component, input } from '@angular/core'
import { BootstrapIconComponent } from '../bootstrap-icon/bootstrap-icon.component'

/**
 * A badge indicating the number of hidden tags.
 */
@Component({
  selector: 'pngx-hidden-tags-badge',
  templateUrl: './hidden-tags-badge.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [BootstrapIconComponent],
})
export class HiddenTagsBadgeComponent {
  readonly count = input.required<number>()
}
