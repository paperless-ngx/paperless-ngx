import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CategoryEditDialogComponent } from './category-edit-dialog.component';

describe('CategoryEditDialogComponent', () => {
  let component: CategoryEditDialogComponent;
  let fixture: ComponentFixture<CategoryEditDialogComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [CategoryEditDialogComponent],
    }).compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(CategoryEditDialogComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
