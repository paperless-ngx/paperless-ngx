import { FileSizePipe } from './file-size.pipe'

describe('FileSizePipe', () => {
  it('should return file size', () => {
    const pipe = new FileSizePipe()
    expect(pipe.transform(1024, 1)).toEqual('1.0 KB')
    expect(pipe.transform(1024 * 1024, 1)).toEqual('1.0 MB')
    expect(
      pipe.transform(1024, {
        bytes: 0,
        KB: 3,
        MB: 1,
        GB: 1,
        TB: 2,
        PB: 2,
      })
    ).toEqual('1.000 KB')
    expect(pipe.transform(NaN, 1)).toEqual('?')
  })
})
