import { Component, OnInit } from '@angular/core';
import { FormControl, FormGroup } from '@angular/forms';
import { NgbActiveModal, NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { Subject } from 'rxjs';
import { first, map, switchMap, takeUntil } from 'rxjs/operators';
import { EditDialogComponent } from 'src/app/components/common/edit-dialog/edit-dialog.component';
import { PaperlessCategory } from 'src/app/data/paperless-category';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { CategoryService } from 'src/app/services/rest/category.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { ToastService } from 'src/app/services/toast.service';
import { CategoryEditDialogComponent } from '../../category-list/category-edit-dialog/category-edit-dialog.component';

@Component({
  selector: 'app-correspondent-edit-dialog',
  templateUrl: './correspondent-edit-dialog.component.html',
  styleUrls: ['./correspondent-edit-dialog.component.scss']
})
export class CorrespondentEditDialogComponent extends EditDialogComponent<PaperlessCorrespondent> implements OnInit {
  categories: PaperlessCategory[]

  unsubscribeNotifier: Subject<any> = new Subject()

  constructor(service: CorrespondentService, private categoryService: CategoryService, activeModal: NgbActiveModal, private modalService: NgbModal, toastService: ToastService) {
    super(service, activeModal, toastService)
  }

  ngOnInit() {
    super.ngOnInit()
    this.categoryService.listAll().pipe(first()).subscribe(result => this.categories = result.results)

  }

  getCreateTitle() {
    return $localize`Create new correspondent`
  }

  getEditTitle() {
    return $localize`Edit correspondent`
  }

  getForm(): FormGroup {
    return new FormGroup({
      name: new FormControl(''),
      category: new FormControl(''),
      matching_algorithm: new FormControl(1),
      match: new FormControl(""),
      is_insensitive: new FormControl(true)
    })
  }

  createCategory(newName: string) {
    var modal = this.modalService.open(CategoryEditDialogComponent, {backdrop: 'static'})
    modal.componentInstance.dialogMode = 'create'
    if (newName) modal.componentInstance.object = { name: newName }
    modal.componentInstance.success.pipe(switchMap(newCategory => {
      return this.categoryService.listAll().pipe(map(categories => ({newCategory, categories})))
    }))
    .pipe(takeUntil(this.unsubscribeNotifier))
    .subscribe(({newCategory, categories}) => {
      this.categories = categories.results
      this.objectForm.get('category').setValue(newCategory.id)
    })
  }
}
