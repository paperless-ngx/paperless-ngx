import { Component, forwardRef, Input, OnInit } from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import { first } from 'rxjs/operators'
import { PaperlessGroup } from 'src/app/data/paperless-group'
import { GroupService } from 'src/app/services/rest/group.service'
import { AbstractInputComponent } from '../../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => PermissionsGroupComponent),
      multi: true,
    },
  ],
  selector: 'pngx-permissions-group',
  templateUrl: './permissions-group.component.html',
  styleUrls: ['./permissions-group.component.scss'],
})
export class PermissionsGroupComponent extends AbstractInputComponent<PaperlessGroup> {
  groups: PaperlessGroup[]

  constructor(groupService: GroupService) {
    super()
    groupService
      .listAll()
      .pipe(first())
      .subscribe((result) => (this.groups = result.results))
  }
}
