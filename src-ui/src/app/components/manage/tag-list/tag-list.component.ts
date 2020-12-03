import { Component } from '@angular/core';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { TAG_COLOURS, PaperlessTag } from 'src/app/data/paperless-tag';
import { TagService } from 'src/app/services/rest/tag.service';
import { CorrespondentEditDialogComponent } from '../correspondent-list/correspondent-edit-dialog/correspondent-edit-dialog.component';
import { GenericListComponent } from '../generic-list/generic-list.component';
import { TagEditDialogComponent } from './tag-edit-dialog/tag-edit-dialog.component';

@Component({
  selector: 'app-tag-list',
  templateUrl: './tag-list.component.html',
  styleUrls: ['./tag-list.component.scss']
})
export class TagListComponent extends GenericListComponent<PaperlessTag> {

  constructor(tagService: TagService, modalService: NgbModal) {
    super(tagService, modalService, TagEditDialogComponent)
  }

  getColor(id) {
    var color = TAG_COLOURS.find(c => c.id == id)
    if (color) {
      return color
    }
    return { id: id, name: id, textColor: "#ffffff" }
  }

  getObjectName(object: PaperlessTag) {
    return `tag '${object.name}'`
  }
}
