import { Component, Input } from '@angular/core'
import { Tag } from 'src/app/data/tag'
import {
  PermissionAction,
  PermissionsService,
  PermissionType,
} from 'src/app/services/permissions.service'
import { TagService } from 'src/app/services/rest/tag.service'

@Component({
  selector: 'pngx-tag',
  templateUrl: './tag.component.html',
  styleUrls: ['./tag.component.scss'],
})
export class TagComponent {
  private _tag: Tag
  private _tagID: number

  constructor(
    private permissionsService: PermissionsService,
    private tagService: TagService
  ) {}

  @Input()
  public set tag(tag: Tag) {
    this._tag = tag
  }

  public get tag(): Tag {
    return this._tag
  }

  @Input()
  set tagID(tagID: number) {
    if (tagID !== this._tagID) {
      this._tagID = tagID
      if (
        this.permissionsService.currentUserCan(
          PermissionAction.View,
          PermissionType.Tag
        )
      ) {
        this.tagService.getCached(this._tagID).subscribe((tag) => {
          this.tag = tag
        })
      }
    }
  }

  @Input()
  linkTitle: string = ''

  @Input()
  clickable: boolean = false
}
