import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FileUploadWidgetComponent } from './file-upload-widget.component';

describe('FileUploadWidgetComponent', () => {
  let component: FileUploadWidgetComponent;
  let fixture: ComponentFixture<FileUploadWidgetComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ FileUploadWidgetComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(FileUploadWidgetComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
