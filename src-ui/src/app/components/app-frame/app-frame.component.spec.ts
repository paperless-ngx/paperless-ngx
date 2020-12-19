import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AppFrameComponent } from './app-frame.component';

describe('AppFrameComponent', () => {
  let component: AppFrameComponent;
  let fixture: ComponentFixture<AppFrameComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ AppFrameComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(AppFrameComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
