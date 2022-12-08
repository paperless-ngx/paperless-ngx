import { Component, forwardRef, Input, OnInit } from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import { first } from 'rxjs/operators'
import { PaperlessGroup } from 'src/app/data/paperless-group'
import { GroupService } from 'src/app/services/rest/group.service'
import { SettingsService } from 'src/app/services/settings.service'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => PermissionsGroupComponent),
      multi: true,
    },
  ],
  selector: 'app-permissions-group',
  templateUrl: './permissions-group.component.html',
  styleUrls: ['./permissions-group.component.scss'],
})
export class PermissionsGroupComponent
  extends AbstractInputComponent<PaperlessGroup>
  implements OnInit
{
  groups: PaperlessGroup[]

  @Input()
  type: string

  constructor(groupService: GroupService, settings: SettingsService) {
    super()
    groupService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.groups = result.results))
  }

  ngOnInit(): void {
    if (this.type == 'view') {
      this.title = $localize`Groups can view`
    } else if (this.type == 'change') {
      this.title = $localize`Groups can edit`
      this.hint = $localize`Edit permissions also grant viewing permissions`
    }

    super.ngOnInit()
  }
}
