using UnityEngine;

public class Kamera : MonoBehaviour
{
    public float hiz = 5f;

    void LateUpdate()
    {
        var y = Input.GetAxis("Vertical");
        var x = Input.GetAxis("Horizontal");
        transform.position += new Vector3(x, y, 0) * hiz * Time.deltaTime;
    }
}
