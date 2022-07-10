import { Component } from '@angular/core';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { FILTER_CATEGORY } from 'src/app/data/filter-rule-type';
import { PaperlessCategory } from 'src/app/data/paperless-category';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { CategoryService } from 'src/app/services/rest/category.service';
import { ToastService } from 'src/app/services/toast.service';
import { GenericListComponent } from '../generic-list/generic-list.component';
import { CategoryEditDialogComponent } from './category-edit-dialog/category-edit-dialog.component';

@Component({
  selector: 'app-category-list',
  templateUrl: './category-list.component.html',
  styleUrls: ['./category-list.component.scss'],
})
export class CategoryListComponent extends GenericListComponent<PaperlessCategory> {
  constructor(
    categorysService: CategoryService,
    modalService: NgbModal,
    private list: DocumentListViewService,
    toastService: ToastService
  ) {
    super(
      categorysService,
      modalService,
      CategoryEditDialogComponent,
      toastService
    );
  }

  getDeleteMessage(object: PaperlessCategory) {
    return $localize`Do you really want to delete the category "${object.name}"?`;
  }
}
