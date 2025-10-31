import {useEffect} from 'react';

export default function useEvent(type, handler, options) {
    useEffect(() => {
        window.addEventListener(type, handler, options);
        return () => window.removeEventListener(type, handler, options);
    }, [type, handler, options]);
}
