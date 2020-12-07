import { Component } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { TAG_COLOURS, PaperlessTag } from 'src/app/data/paperless-tag';
import { TagService } from 'src/app/services/rest/tag.service';
import { environment } from 'src/environments/environment';
import { CorrespondentEditDialogComponent } from '../correspondent-list/correspondent-edit-dialog/correspondent-edit-dialog.component';
import { GenericListComponent } from '../generic-list/generic-list.component';
import { TagEditDialogComponent } from './tag-edit-dialog/tag-edit-dialog.component';

@Component({
  selector: 'app-tag-list',
  templateUrl: './tag-list.component.html',
  styleUrls: ['./tag-list.component.scss']
})
export class TagListComponent extends GenericListComponent<PaperlessTag> {

  constructor(tagService: TagService, modalService: NgbModal, private titleService: Title) {
    super(tagService, modalService, TagEditDialogComponent)
  }


  ngOnInit(): void {
    super.ngOnInit()
    this.titleService.setTitle(`Tags - ${environment.appTitle}`)
  }

  getColor(id) {
    return TAG_COLOURS.find(c => c.id == id)
  }

  getObjectName(object: PaperlessTag) {
    return `tag '${object.name}'`
  }
}
